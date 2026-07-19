from __future__ import annotations

import gc
import logging
import os
from collections import defaultdict
from functools import partial
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from scipy.stats import norm
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from ._config import SpatialLdscConfig
from ._style import Colors, EMOJI
from ._jackknife import LstsqJackknifeFast
from ._regression_read import _read_ref_ld_v2, _read_sumstats, _read_w_ld

logger = logging.getLogger(__name__)


def _coef_new(jknife, nbar):
    """Calculate coefficients adjusted by mean sample size."""

    est_ = jknife.jknife_est[0, 0] / nbar
    se_ = jknife.jknife_se[0, 0] / nbar
    return est_, se_


def append_intercept(x):
    """Append an intercept term to the design matrix."""

    intercept = np.ones((x.shape[0], 1))
    return np.concatenate((x, intercept), axis=1)


def filter_sumstats_by_chisq(sumstats, chisq_max):
    """Filter summary statistics based on chi-squared threshold."""

    if chisq_max is None:
        chisq_max = max(0.001 * sumstats.N.max(), 80)
    sumstats["chisq"] = sumstats.Z**2
    return sumstats[sumstats.chisq < chisq_max]


def aggregate(y, x, n, m, intercept=1):
    """Aggregate helper used in initial weight calculation."""

    numerator = m * (np.mean(y) - intercept)
    denominator = np.mean(np.multiply(x, n))
    return numerator / denominator


def weights(ld, w_ld, n, m, hsq, intercept=1):
    """Calculate regression weights."""

    m = float(m)
    hsq = np.clip(hsq, 0.0, 1.0)
    ld = np.maximum(ld, 1.0)
    w_ld = np.maximum(w_ld, 1.0)
    c = hsq * n / m
    het_w = 1.0 / (2 * np.square(intercept + np.multiply(c, ld)))
    oc_w = 1.0 / w_ld
    return np.multiply(het_w, oc_w)


def get_weight_optimized(sumstats, x_tot_precomputed, m_tot, w_ld, intercept=1):
    """Calculate initial weights with the LDSC heuristic."""

    tot_agg = aggregate(sumstats.chisq, x_tot_precomputed, sumstats.N, m_tot, intercept)
    initial_w = weights(
        x_tot_precomputed, w_ld.LD_weights.values, sumstats.N.values, m_tot, tot_agg, intercept
    )
    return np.sqrt(initial_w)


def jackknife_for_processmap(
    spot_id,
    spatial_annotation,
    ref_ld_baseline_column_sum,
    sumstats,
    baseline_annotation,
    w_ld_common_snp,
    nbar,
    n_blocks,
):
    """Perform jackknife resampling for one spot."""

    spot_spatial_annotation = spatial_annotation[:, spot_id]
    spot_x_tot_precomputed = spot_spatial_annotation + ref_ld_baseline_column_sum
    initial_w = (
        get_weight_optimized(
            sumstats,
            x_tot_precomputed=spot_x_tot_precomputed,
            m_tot=10000,
            w_ld=w_ld_common_snp,
            intercept=1,
        )
        .astype(np.float32)
        .reshape((-1, 1))
    )
    initial_w_scaled = initial_w / np.sum(initial_w)
    baseline_annotation_spot = baseline_annotation * initial_w_scaled
    spatial_annotation_spot = spot_spatial_annotation.reshape((-1, 1)) * initial_w_scaled
    chisq = sumstats.chisq.values.reshape((-1, 1))
    y = chisq * initial_w_scaled
    x_focal = np.concatenate((spatial_annotation_spot, baseline_annotation_spot), axis=1)
    try:
        jknife = LstsqJackknifeFast(x_focal, y, n_blocks)
    except np.linalg.LinAlgError:
        return np.nan, np.nan
    return _coef_new(jknife, nbar)


def _preprocess_sumstats(trait_name, sumstat_file_path, baseline_and_w_ld_common_snp, chisq_max):
    """Preprocess one GWAS summary-statistics file."""

    sumstats = _read_sumstats(fh=sumstat_file_path, alleles=False, dropna=False)
    sumstats.set_index("SNP", inplace=True)
    sumstats = sumstats.astype(np.float32)
    sumstats = filter_sumstats_by_chisq(sumstats, chisq_max)
    common_snp = baseline_and_w_ld_common_snp.intersection(sumstats.index)
    if len(common_snp) < 200000:
        print(
            f"{Colors.WARNING}⚠️  WARNING: number of SNPs less than 200k; "
            f"for {trait_name} this is almost always bad.{Colors.ENDC}"
        )
    sumstats = sumstats.loc[common_snp]
    sumstats["common_index_pos"] = pd.Index(baseline_and_w_ld_common_snp).get_indexer(
        sumstats.index
    )
    return sumstats


def _get_sumstats_with_common_snp_from_sumstats_dict(
    sumstats_config_dict, baseline_and_w_ld_common_snp, chisq_max=None
):
    """Get summary statistics with a common SNP set across all traits."""

    for sumstat_file_path in sumstats_config_dict.values():
        if not os.path.exists(sumstat_file_path):
            raise FileNotFoundError(f"{sumstat_file_path} not found")

    sumstats_cleaned_dict = {}
    for trait_name, sumstat_file_path in sumstats_config_dict.items():
        sumstats_cleaned_dict[trait_name] = _preprocess_sumstats(
            trait_name, sumstat_file_path, baseline_and_w_ld_common_snp, chisq_max
        )

    common_snp_among_all_sumstats = None
    for sumstats in sumstats_cleaned_dict.values():
        if common_snp_among_all_sumstats is None:
            common_snp_among_all_sumstats = sumstats.index
        else:
            common_snp_among_all_sumstats = common_snp_among_all_sumstats.intersection(
                sumstats.index
            )

    for trait_name, sumstats in sumstats_cleaned_dict.items():
        sumstats_cleaned_dict[trait_name] = sumstats.loc[common_snp_among_all_sumstats]

    return sumstats_cleaned_dict, common_snp_among_all_sumstats


class SpatialLdscQuickMode:
    """Handle quick-mode precomputed SNP-gene weight matrices."""

    def __init__(self, config: SpatialLdscConfig, common_snp_among_all_sumstats_pos):
        self.config = config
        mk_score = pd.read_feather(config.mkscore_feather_path).set_index("HUMAN_GENE_SYM")
        mk_score_genes = mk_score.index
        snp_gene_weight_adata = ad.read_h5ad(config.snp_gene_weight_adata_path)
        common_genes = mk_score_genes.intersection(snp_gene_weight_adata.var.index)
        col_idx = snp_gene_weight_adata.var.index.get_indexer(common_genes)
        self.snp_gene_weight_matrix = snp_gene_weight_adata.X[common_snp_among_all_sumstats_pos][
            :, col_idx
        ]
        self.mk_score_common = mk_score.loc[common_genes]
        self.chunk_starts = list(
            range(0, self.mk_score_common.shape[1], self.config.spots_per_chunk_quick_mode)
        )

    def fetch_ldscore_by_chunk(self, chunk_index):
        """Fetch one chunk of quick-mode spatial LD scores."""

        chunk_start = self.chunk_starts[chunk_index]
        mk_score_chunk = self.mk_score_common.iloc[
            :, chunk_start : chunk_start + self.config.spots_per_chunk_quick_mode
        ]
        ldscore_chunk = self.calculate_ldscore_use_snp_gene_weight_matrix_by_chunk(
            mk_score_chunk, drop_dummy_na=False
        )
        spots_name = self.mk_score_common.columns[
            chunk_start : chunk_start + self.config.spots_per_chunk_quick_mode
        ]
        return ldscore_chunk, spots_name

    def calculate_ldscore_use_snp_gene_weight_matrix_by_chunk(
        self, mk_score_chunk, drop_dummy_na=True
    ):
        """Calculate LD scores from the precomputed SNP-gene weight matrix."""

        if drop_dummy_na:
            return self.snp_gene_weight_matrix[:, :-1] @ mk_score_chunk
        return self.snp_gene_weight_matrix @ mk_score_chunk


def determine_total_chunks(config):
    """Determine total number of LD-score chunks."""

    if config.ldscore_save_format != "quick_mode":
        raise ValueError(f"Unsupported ldscore_save_format: {config.ldscore_save_format}")
    s_ldsc = SpatialLdscQuickMode(config, [])
    return len(s_ldsc.chunk_starts)


def determine_chunk_range(config, total_chunk_number_found):
    """Determine which chunk range to process."""

    if config.all_chunk is None:
        if config.chunk_range is not None:
            if not (1 <= config.chunk_range[0] <= total_chunk_number_found) or not (
                1 <= config.chunk_range[1] <= total_chunk_number_found
            ):
                raise ValueError("Chunk range out of bound. It should be in [1, all_chunk]")
            return config.chunk_range
        return 1, total_chunk_number_found
    return 1, config.all_chunk


def save_results(output_dict, config, running_chunk_number, start_chunk, end_chunk):
    """Save spatial-LDSC results."""

    out_dir = config.ldsc_save_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for trait_name, out_chunk_list in output_dict.items():
        out_all = pd.concat(out_chunk_list, axis=0)
        if running_chunk_number == determine_total_chunks(config):
            out_file_name = out_dir / f"{config.sample_name}_{trait_name}.csv.gz"
        else:
            out_file_name = (
                out_dir / f"{config.sample_name}_{trait_name}_chunk{start_chunk}-{end_chunk}.csv.gz"
            )
        out_all["spot"] = out_all.index
        out_all = out_all[["spot", "beta", "se", "z", "p"]]
        out_all["p"] = out_all["p"].clip(1e-300, 1)
        out_all.to_csv(out_file_name, compression="gzip", index=False)


def run_spatial_ldsc(config: SpatialLdscConfig) -> Path:
    """Run spatial LDSC analysis."""

    if config.ldscore_save_format != "quick_mode":
        raise ImportError("Only quick_mode spatial_ldsc is supported in this integration.")
    if not Path(config.mkscore_feather_path).exists():
        raise FileNotFoundError(f"{config.mkscore_feather_path} does not exist.")
    if not Path(config.snp_gene_weight_adata_path).exists():
        raise FileNotFoundError(f"{config.snp_gene_weight_adata_path} does not exist.")
    if not Path(config.w_file).parent.exists():
        raise FileNotFoundError(f"{config.w_file} does not exist.")

    w_ld = _read_w_ld(str(config.w_file))
    w_ld.set_index("SNP", inplace=True)

    ld_file_baseline = f"{config.ldscore_save_dir}/baseline/baseline."
    ref_ld_baseline = _read_ref_ld_v2(ld_file_baseline)
    baseline_and_w_ld_common_snp = ref_ld_baseline.index.intersection(w_ld.index)

    sumstats_cleaned_dict, common_snp_among_all_sumstats = (
        _get_sumstats_with_common_snp_from_sumstats_dict(
            config.sumstats_config_dict, baseline_and_w_ld_common_snp, chisq_max=config.chisq_max
        )
    )
    common_snp_among_all_sumstats_pos = ref_ld_baseline.index.get_indexer(
        common_snp_among_all_sumstats
    )

    ref_ld_baseline = ref_ld_baseline.loc[common_snp_among_all_sumstats]
    w_ld = w_ld.loc[common_snp_among_all_sumstats]

    if config.use_additional_baseline_annotation:
        ld_file_baseline_additional = f"{config.ldscore_save_dir}/additional_baseline/baseline."
        ref_ld_baseline_additional = _read_ref_ld_v2(ld_file_baseline_additional)
        ref_ld_baseline_additional = ref_ld_baseline_additional.loc[common_snp_among_all_sumstats]
        ref_ld_baseline = pd.concat([ref_ld_baseline, ref_ld_baseline_additional], axis=1)
        del ref_ld_baseline_additional

    s_ldsc = SpatialLdscQuickMode(config, common_snp_among_all_sumstats_pos)
    total_chunk_number_found = len(s_ldsc.chunk_starts)
    start_chunk, end_chunk = determine_chunk_range(config, total_chunk_number_found)
    running_chunk_number = end_chunk - start_chunk + 1

    output_dict = defaultdict(list)
    total_chunks = running_chunk_number * len(sumstats_cleaned_dict)
    pbar = tqdm(total=total_chunks, desc="Running spatial_ldsc")
    for chunk_index in range(start_chunk, end_chunk + 1):
        ref_ld_spatial, spatial_annotation_cnames = s_ldsc.fetch_ldscore_by_chunk(chunk_index - 1)
        ref_ld_baseline_column_sum = ref_ld_baseline.sum(axis=1).values

        for trait_name, sumstats in sumstats_cleaned_dict.items():
            spatial_annotation = ref_ld_spatial.astype(np.float32, copy=False)
            baseline_annotation = ref_ld_baseline.copy().astype(np.float32, copy=False)
            w_ld_common_snp = w_ld.astype(np.float32, copy=False)

            baseline_annotation = (
                baseline_annotation * sumstats.N.values.reshape((-1, 1)) / sumstats.N.mean()
            )
            baseline_annotation = append_intercept(baseline_annotation)

            nbar = sumstats.N.mean()
            chunk_size = spatial_annotation.shape[1]

            jackknife_func = partial(
                jackknife_for_processmap,
                spatial_annotation=spatial_annotation,
                ref_ld_baseline_column_sum=ref_ld_baseline_column_sum,
                sumstats=sumstats,
                baseline_annotation=baseline_annotation,
                w_ld_common_snp=w_ld_common_snp,
                nbar=nbar,
                n_blocks=config.n_blocks,
            )

            with ThreadPoolExecutor(max_workers=config.num_processes) as executor:
                out_chunk = list(executor.map(jackknife_func, range(chunk_size), chunksize=10))

            out_chunk = pd.DataFrame.from_records(
                out_chunk, columns=["beta", "se"], index=spatial_annotation_cnames
            )
            out_chunk = out_chunk.dropna()
            out_chunk["z"] = out_chunk.beta / out_chunk.se
            out_chunk["p"] = norm.sf(out_chunk["z"])
            output_dict[trait_name].append(out_chunk)

            del spatial_annotation, baseline_annotation, w_ld_common_snp
            gc.collect()
            pbar.update(1)
    pbar.close()

    save_results(output_dict, config, running_chunk_number, start_chunk, end_chunk)
    return config.ldsc_save_dir
