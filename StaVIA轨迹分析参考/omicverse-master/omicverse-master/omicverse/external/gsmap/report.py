from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from . import cauchy_combination
from ._config import CauchyCombinationConfig, ReportConfig
from ._style import Colors, EMOJI
from .diagnosis import run_diagnosis

logger = logging.getLogger(__name__)

template_dir = Path(__file__).resolve().parent / "templates"
env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template("report_template.html")


def load_cauchy_table(csv_file):
    """Load the cauchy-combination table for HTML rendering."""

    dataframe = pd.read_csv(csv_file, compression="gzip")
    return dataframe[["annotation", "p_cauchy", "p_median"]].to_dict(orient="records")


def load_gene_diagnostic_info(csv_file):
    """Load the top rows of the gene-diagnostic info CSV."""

    dataframe = pd.read_csv(csv_file)
    return dataframe.head(50).to_dict(orient="records")


def embed_html_content(file_path):
    """Read one HTML fragment into memory for template embedding."""

    with open(file_path, encoding="utf-8") as handle:
        return handle.read()


def check_and_run_cauchy_combination(config: ReportConfig):
    """Ensure the cauchy-combination CSV exists before building the report."""

    cauchy_result_file = config.get_cauchy_result_file(config.trait_name)
    if not cauchy_result_file.exists():
        cauchy_config = CauchyCombinationConfig(
            workdir=config.workdir,
            sample_name=config.sample_name,
            annotation=config.annotation,
            trait_name=config.trait_name,
        )
        cauchy_combination.run_cauchy_combination(cauchy_config)
    return load_cauchy_table(cauchy_result_file)


def run_report(config: ReportConfig, run_parameters=None):
    """Generate the final gsMap HTML report for one trait."""

    run_diagnosis(config)

    report_dir = config.get_report_dir(config.trait_name)
    report_dir.mkdir(parents=True, exist_ok=True)
    gene_info_file = config.get_gene_diagnostic_info_save_path(config.trait_name)
    gene_diagnostic_info = load_gene_diagnostic_info(gene_info_file)
    cauchy_table = check_and_run_cauchy_combination(config)

    gss_plot_dir = config.get_gss_plot_dir(config.trait_name)
    plot_select_gene_list = config.get_gss_plot_select_gene_file(config.trait_name).read_text(
        encoding="utf-8"
    ).splitlines()

    gene_plots = []
    for gene_name in plot_select_gene_list:
        expression_png = gss_plot_dir / f"{config.sample_name}_{gene_name}_Expression_Distribution.png"
        gss_png = gss_plot_dir / f"{config.sample_name}_{gene_name}_GSS_Distribution.png"
        if not expression_png.exists() or not gss_png.exists():
            continue
        gene_plots.append(
            {
                "name": gene_name,
                "expression_plot": expression_png.relative_to(report_dir),
                "gss_plot": gss_png.relative_to(report_dir),
            }
        )

    title = f"{config.sample_name} Genetic Spatial Mapping Report"
    genetic_mapping_plot = embed_html_content(config.get_gsmap_html_plot_save_path(config.trait_name))
    manhattan_plot = embed_html_content(config.get_manhattan_html_plot_path(config.trait_name))

    parameters = {
        "Sample Name": config.sample_name,
        "Trait Name": config.trait_name,
        "Summary Statistics File": config.sumstats_file,
        "HDF5 Path": config.hdf5_with_latent_path,
        "Annotation": config.annotation,
        "Spatial LDSC Save Directory": config.ldsc_save_dir,
        "Cauchy Directory": config.cauchy_save_dir,
        "Report Directory": config.get_report_dir(config.trait_name),
        "gsMap Report File": config.get_gsmap_report_file(config.trait_name),
        "Gene Diagnostic Info File": config.get_gene_diagnostic_info_save_path(config.trait_name),
        "Report Generation Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if run_parameters is not None:
        parameters.update(run_parameters)

    output_html = template.render(
        title=title,
        genetic_mapping_plot=genetic_mapping_plot,
        manhattan_plot=manhattan_plot,
        cauchy_table=cauchy_table,
        gene_plots=gene_plots,
        gsmap_version="omicverse-gsmap",
        parameters=parameters,
        gene_diagnostic_info=gene_diagnostic_info,
    )

    report_file = config.get_gsmap_report_file(config.trait_name)
    with open(report_file, "w", encoding="utf-8") as handle:
        handle.write(output_html)

    print(
        f"{EMOJI['done']} {Colors.GREEN}Report generated successfully at {report_file}.{Colors.ENDC}"
    )
    return report_file
