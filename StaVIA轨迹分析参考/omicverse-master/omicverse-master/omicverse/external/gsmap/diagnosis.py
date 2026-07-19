from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
from scipy.stats import norm

from ._config import DiagnosisConfig
from ._manhattan_plot import manhattan_plot
from ._regression_read import _read_chr_files
from ._style import Colors, EMOJI
from ._visualize import draw_scatter, estimate_point_size_for_plot, load_ldsc, load_st_coord

logger = logging.getLogger(__name__)


def write_plot_image(fig, output_path):
    """Write one static plot image when kaleido is available."""

    try:
        fig.write_image(output_path)
        return output_path
    except ValueError as exc:
        if "Kaleido package" not in str(exc):
            raise
        print(
            f"{Colors.WARNING}⚠️  Skipping static image export for {output_path} "
            f"because kaleido is not installed.{Colors.ENDC}"
        )
        return None


def convert_z_to_p(gwas_data):
    """Convert GWAS Z-scores to two-sided p-values."""

    gwas_data["P"] = norm.sf(abs(gwas_data["Z"])) * 2
    gwas_data["P"] = gwas_data["P"].clip(lower=1e-300)
    return gwas_data


def load_gene_diagnostic_info(config: DiagnosisConfig, adata):
    """Load or compute the gene-diagnostic summary table."""

    gene_info_path = config.get_gene_diagnostic_info_save_path(config.trait_name)
    if gene_info_path.exists():
        return pd.read_csv(gene_info_path)
    return compute_gene_diagnostic_info(config, adata)


def compute_gene_diagnostic_info(config: DiagnosisConfig, adata):
    """Compute gene-level diagnostic summaries used by the final report."""

    mk_score = pd.read_feather(config.mkscore_feather_path)
    mk_score.set_index("HUMAN_GENE_SYM", inplace=True)
    mk_score = mk_score.T
    trait_ldsc_result = load_ldsc(config.get_ldsc_result_file(config.trait_name))

    common_spots = mk_score.index.intersection(trait_ldsc_result.index).intersection(adata.obs_names)
    mk_score = mk_score.loc[common_spots]
    trait_ldsc_result = trait_ldsc_result.loc[common_spots]
    adata = adata[common_spots].copy()

    has_variation = (~mk_score.eq(mk_score.iloc[0], axis=1)).any()
    mk_score = mk_score.loc[:, has_variation]

    corr = mk_score.corrwith(trait_ldsc_result["logp"])
    corr.name = "PCC"

    grouped_mk_score = mk_score.groupby(adata.obs[config.annotation], observed=False).median()
    max_annotations = grouped_mk_score.idxmax()

    gene_info = pd.DataFrame(
        {
            "Gene": max_annotations.index,
            "Annotation": max_annotations.values,
            "Median_GSS": grouped_mk_score.max().values,
        }
    ).merge(corr, left_on="Gene", right_index=True)

    gene_info = gene_info[["Gene", "Annotation", "Median_GSS", "PCC"]]
    gene_info = gene_info.drop_duplicates().dropna(subset=["Gene"])
    gene_info.sort_values("PCC", ascending=False, inplace=True)

    gene_info_path = config.get_gene_diagnostic_info_save_path(config.trait_name)
    gene_info_path.parent.mkdir(parents=True, exist_ok=True)
    gene_info.to_csv(gene_info_path, index=False)
    return gene_info.reset_index(drop=True)


def load_gwas_data(config: DiagnosisConfig):
    """Load the GWAS summary statistics used by diagnosis."""

    gwas_data = pd.read_csv(config.sumstats_file, compression="gzip", sep="\t")
    return convert_z_to_p(gwas_data)


def load_snp_gene_pairs(config: DiagnosisConfig):
    """Load quick-mode SNP-gene pair annotations across chromosomes."""

    snp_gene_pair_prefix = config.ldscore_save_dir / "SNP_gene_pair" / "SNP_gene_pair_chr"
    return pd.concat(
        [
            pd.read_feather(file_path)
            for file_path in _read_chr_files(snp_gene_pair_prefix.as_posix(), suffix=".feather")
        ]
    )


def filter_snps(gwas_data_with_gene_annotation_sort, subsample_snp_number):
    """Reduce Manhattan plot density while preserving strong signals."""

    pass_suggestive_line_mask = gwas_data_with_gene_annotation_sort["P"] < 1e-5
    pass_suggestive_line_number = pass_suggestive_line_mask.sum()
    if pass_suggestive_line_number > subsample_snp_number:
        return gwas_data_with_gene_annotation_sort[pass_suggestive_line_mask].SNP
    return gwas_data_with_gene_annotation_sort.head(subsample_snp_number).SNP


def generate_manhattan_plot(config: DiagnosisConfig, adata):
    """Generate the HTML Manhattan plot for the report."""

    gwas_data = load_gwas_data(config)
    snp_gene_pair = load_snp_gene_pairs(config)
    gwas_data_with_gene = snp_gene_pair.merge(gwas_data, on="SNP", how="inner").rename(
        columns={"gene_name": "GENE"}
    )
    gene_info = load_gene_diagnostic_info(config, adata)
    merged = gwas_data_with_gene.merge(gene_info, left_on="GENE", right_on="Gene", how="left")
    merged = merged[~merged["Annotation"].isna()]
    merged = merged.sort_values("P")

    if merged.empty:
        raise ValueError("Filtered GWAS data is empty, cannot create Manhattan plot.")

    snps_to_plot = filter_snps(merged, subsample_snp_number=100_000)
    plot_df = merged[merged["SNP"].isin(snps_to_plot)].reset_index(drop=True)
    if plot_df.empty:
        raise ValueError("No SNPs passed filtering criteria for Manhattan plot.")

    plot_df["Annotation_text"] = (
        "PCC: "
        + plot_df["PCC"].round(2).astype(str)
        + "<br>Annotation: "
        + plot_df["Annotation"].astype(str)
    )

    fig = manhattan_plot(
        dataframe=plot_df,
        title="gsMap Diagnosis Manhattan Plot",
        point_size=3,
        highlight_gene_list=config.selected_genes or gene_info.Gene.iloc[: config.top_corr_genes].tolist(),
        suggestiveline_value=-np.log10(1e-5),
        annotation="Annotation_text",
    )

    save_path = config.get_manhattan_html_plot_path(config.trait_name)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(save_path)
    return save_path


def save_plot(sub_fig, sub_fig_save_dir, sample_name, selected_gene, plot_type):
    """Persist one GSS or expression distribution PNG."""

    save_path = sub_fig_save_dir / f"{sample_name}_{selected_gene}_{plot_type}_Distribution.png"
    sub_fig.update_layout(showlegend=False)
    return write_plot_image(sub_fig, save_path)


def generate_gss_distribution(config: DiagnosisConfig, adata):
    """Generate GSS and expression distribution PNGs for selected genes."""

    mk_score = pd.read_feather(config.mkscore_feather_path).set_index("HUMAN_GENE_SYM").T
    plot_genes = config.selected_genes or load_gene_diagnostic_info(config, adata).Gene.iloc[
        : config.top_corr_genes
    ].tolist()

    if config.customize_fig:
        pixel_width, pixel_height, point_size = (
            config.fig_width,
            config.fig_height,
            config.point_size,
        )
    else:
        (pixel_width, pixel_height), point_size = estimate_point_size_for_plot(adata.obsm["spatial"])

    plot_dir = config.get_gss_plot_dir(config.trait_name)
    plot_dir.mkdir(parents=True, exist_ok=True)
    config.get_gss_plot_select_gene_file(config.trait_name).write_text("\n".join(plot_genes), encoding="utf-8")

    for selected_gene in plot_genes:
        expression_values = adata[:, selected_gene].X
        if hasattr(expression_values, "toarray"):
            expression_values = expression_values.toarray()
        expression_series = pd.Series(
            np.asarray(expression_values, dtype=np.float64).flatten(),
            index=adata.obs.index,
            name="Expression",
        )
        threshold = np.quantile(expression_series, 0.9999)
        expression_series[expression_series > threshold] = threshold

        expression_plot = draw_scatter(
            load_st_coord(adata, expression_series, config.annotation),
            title=f"{selected_gene} (Expression)",
            annotation="annotation",
            color_by="Expression",
            point_size=point_size,
            width=pixel_width,
            height=pixel_height,
        )
        save_plot(expression_plot, plot_dir, config.sample_name, selected_gene, "Expression")

        gss_plot = draw_scatter(
            load_st_coord(adata, mk_score[selected_gene].rename("GSS"), config.annotation),
            title=f"{selected_gene} (GSS)",
            annotation="annotation",
            color_by="GSS",
            point_size=point_size,
            width=pixel_width,
            height=pixel_height,
        )
        save_plot(gss_plot, plot_dir, config.sample_name, selected_gene, "GSS")

    return plot_dir


def generate_gsmap_plot(config: DiagnosisConfig, adata):
    """Generate the HTML gsMap spatial plot for the report."""

    trait_ldsc_result = load_ldsc(config.get_ldsc_result_file(config.trait_name))
    space_coord_concat = load_st_coord(adata, trait_ldsc_result, annotation=config.annotation)

    if config.customize_fig:
        pixel_width, pixel_height, point_size = (
            config.fig_width,
            config.fig_height,
            config.point_size,
        )
    else:
        (pixel_width, pixel_height), point_size = estimate_point_size_for_plot(adata.obsm["spatial"])

    fig = draw_scatter(
        space_coord_concat,
        title=f"{config.trait_name} (gsMap)",
        point_size=point_size,
        width=pixel_width,
        height=pixel_height,
        annotation=config.annotation,
    )

    output_dir = config.get_gsmap_plot_save_dir(config.trait_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file_html = config.get_gsmap_html_plot_save_path(config.trait_name)
    output_file_png = output_file_html.with_suffix(".png")
    output_file_csv = output_file_html.with_suffix(".csv")

    fig.write_html(output_file_html)
    write_plot_image(fig, output_file_png)
    space_coord_concat.to_csv(output_file_csv)
    return output_file_html


def run_diagnosis(config: DiagnosisConfig):
    """Generate the intermediate plot and table assets consumed by the HTML report."""

    adata = sc.read_h5ad(config.hdf5_with_latent_path)
    if "log1p" not in adata.uns and adata.X.max() > 14:
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    if config.plot_type in ["gsMap", "all"]:
        generate_gsmap_plot(config, adata)
    if config.plot_type in ["manhattan", "all"]:
        generate_manhattan_plot(config, adata)
    if config.plot_type in ["GSS", "all"]:
        generate_gss_distribution(config, adata)
