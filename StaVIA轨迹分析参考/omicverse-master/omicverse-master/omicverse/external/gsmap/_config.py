from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from ._style import Colors, EMOJI

logger = logging.getLogger(__name__)


@dataclass
class FindLatentRepresentationsConfig:
    """Configuration for the vendored gsMap latent-representation step."""

    workdir: str
    sample_name: str
    input_hdf5_path: str
    annotation: str | None = None
    data_layer: str = "counts"
    epochs: int = 300
    feat_hidden1: int = 256
    feat_hidden2: int = 128
    feat_cell: int = 3000
    gat_hidden1: int = 64
    gat_hidden2: int = 30
    p_drop: float = 0.1
    gat_lr: float = 0.001
    gcn_decay: float = 0.01
    n_neighbors: int = 11
    label_w: float = 1.0
    rec_w: float = 1.0
    input_pca: bool = True
    n_comps: int = 300
    weighted_adj: bool = False
    nheads: int = 3
    var: bool = False
    convergence_threshold: float = 1e-4
    hierarchically: bool = False
    pearson_residuals: bool = False

    @property
    def hdf5_with_latent_path(self) -> Path:
        """Return the expected output path for the latent-augmented h5ad."""

        return (
            Path(self.workdir)
            / self.sample_name
            / "find_latent_representations"
            / f"{self.sample_name}_add_latent.h5ad"
        )

    @property
    def mkscore_feather_path(self) -> Path:
        """Return the expected output path for latent-to-gene marker scores."""

        return (
            Path(self.workdir)
            / self.sample_name
            / "latent_to_gene"
            / f"{self.sample_name}_gene_marker_score.feather"
        )

    def __post_init__(self) -> None:
        """Validate the reduced config surface used by OmicVerse."""

        if self.hierarchically and self.annotation is None:
            raise ValueError("annotation must be provided when hierarchically is true.")

        if self.annotation is None:
            print(
                f"{Colors.WARNING}⚠️  annotation is not provided. Latent representations will be "
                f"computed for the full dataset.{Colors.ENDC}"
            )


@dataclass
class LatentToGeneConfig:
    """Configuration for the vendored gsMap latent-to-gene step."""

    workdir: str
    sample_name: str
    input_hdf5_path: str | None = None
    no_expression_fraction: bool = False
    latent_representation: str | None = None
    num_neighbour: int = 51
    num_neighbour_spatial: int = 201
    homolog_file: str | None = None
    gM_slices: str | None = None
    annotation: str | None = None
    species: str | None = None

    @property
    def hdf5_with_latent_path(self) -> Path:
        """Return the latent-augmented h5ad path used by downstream steps."""

        if self.input_hdf5_path is not None:
            return Path(self.input_hdf5_path)
        return (
            Path(self.workdir)
            / self.sample_name
            / "find_latent_representations"
            / f"{self.sample_name}_add_latent.h5ad"
        )

    @property
    def mkscore_feather_path(self) -> Path:
        """Return the output path for latent-to-gene marker scores."""

        return (
            Path(self.workdir)
            / self.sample_name
            / "latent_to_gene"
            / f"{self.sample_name}_gene_marker_score.feather"
        )

    def __post_init__(self) -> None:
        """Validate latent-to-gene config and apply OmicVerse defaults."""

        if self.latent_representation is None:
            self.latent_representation = "latent_GVAE"

        if self.gM_slices is not None and not Path(self.gM_slices).exists():
            raise FileNotFoundError(f"{self.gM_slices} does not exist.")


@dataclass
class GenerateLdscoreConfig:
    """Configuration for the vendored gsMap ldscore step."""

    workdir: str
    sample_name: str
    mkscore_feather_path: str | None = None
    chrom: int | str = "all"
    bfile_root: str | None = None
    gtf_annotation_file: str | None = None
    gene_window_size: int = 50000
    keep_snp_root: str | None = None
    enhancer_annotation_file: str | None = None
    snp_multiple_enhancer_strategy: str = "max_mkscore"
    gene_window_enhancer_priority: str | None = None
    additional_baseline_annotation: str | None = None
    spots_per_chunk: int = 1000
    ld_wind: int = 1
    ld_unit: str = "CM"
    ldscore_save_format: str = "quick_mode"
    save_pre_calculate_snp_gene_weight_matrix: bool = False
    baseline_annotation_dir: str | Path | None = None
    snp_gene_pair_dir: str | Path | None = None

    @property
    def ldscore_save_dir(self) -> Path:
        """Return the output directory for generated ldscore files."""

        return Path(self.workdir) / self.sample_name / "generate_ldscore"

    def __post_init__(self) -> None:
        """Validate the OmicVerse-supported ldscore config surface."""

        if self.ldscore_save_format == "quick_mode":
            if self.baseline_annotation_dir is None:
                raise ValueError("baseline_annotation_dir must be provided in quick_mode.")
            if self.snp_gene_pair_dir is None:
                raise ValueError("snp_gene_pair_dir must be provided in quick_mode.")

            self.baseline_annotation_dir = Path(self.baseline_annotation_dir)
            self.snp_gene_pair_dir = Path(self.snp_gene_pair_dir)

            if not self.baseline_annotation_dir.exists():
                raise FileNotFoundError(f"{self.baseline_annotation_dir} does not exist.")
            if not self.snp_gene_pair_dir.exists():
                raise FileNotFoundError(f"{self.snp_gene_pair_dir} does not exist.")
            return

        if self.mkscore_feather_path is None:
            self.mkscore_feather_path = str(
                Path(self.workdir)
                / self.sample_name
                / "latent_to_gene"
                / f"{self.sample_name}_gene_marker_score.feather"
            )


@dataclass
class SpatialLdscConfig:
    """Configuration for the vendored gsMap spatial-LDSC step."""

    workdir: str
    sample_name: str
    w_file: str | Path | None = None
    use_additional_baseline_annotation: bool = True
    trait_name: str | None = None
    sumstats_file: str | None = None
    sumstats_config_file: str | None = None
    num_processes: int = 4
    not_M_5_50: bool = False
    n_blocks: int = 200
    chisq_max: int | None = None
    all_chunk: int | None = None
    chunk_range: tuple[int, int] | None = None
    ldscore_save_format: str = "quick_mode"
    spots_per_chunk_quick_mode: int = 1000
    snp_gene_weight_adata_path: str | Path | None = None
    mkscore_feather_path: str | Path | None = None

    @property
    def ldscore_save_dir(self) -> Path:
        """Return the input ldscore directory for spatial LDSC."""

        return Path(self.workdir) / self.sample_name / "generate_ldscore"

    @property
    def ldsc_save_dir(self) -> Path:
        """Return the output directory for spatial LDSC results."""

        return Path(self.workdir) / self.sample_name / "spatial_ldsc"

    def __post_init__(self) -> None:
        """Validate spatial-LDSC config and set quick-mode defaults."""

        self.sumstats_config_dict = {}

        if self.sumstats_file is None and self.sumstats_config_file is None:
            raise ValueError("One of sumstats_file and sumstats_config_file must be provided.")
        if self.sumstats_file is not None and self.sumstats_config_file is not None:
            raise ValueError(
                "Only one of sumstats_file and sumstats_config_file must be provided."
            )
        if self.sumstats_file is not None and self.trait_name is None:
            raise ValueError("trait_name must be provided if sumstats_file is provided.")
        if self.sumstats_config_file is not None and self.trait_name is not None:
            raise ValueError(
                "trait_name must not be provided if sumstats_config_file is provided."
            )

        if self.sumstats_config_file is not None:
            import yaml

            with open(self.sumstats_config_file, encoding="utf-8") as handle:
                config = yaml.load(handle, Loader=yaml.FullLoader)
            for trait_name, sumstats_file in config.items():
                if not Path(sumstats_file).exists():
                    raise FileNotFoundError(f"{sumstats_file} does not exist.")
                self.sumstats_config_dict[trait_name] = sumstats_file
        else:
            if not Path(self.sumstats_file).exists():
                raise FileNotFoundError(f"{self.sumstats_file} does not exist.")
            self.sumstats_config_dict[self.trait_name] = self.sumstats_file

        if self.w_file is None:
            w_ld_dir = self.ldscore_save_dir / "w_ld"
            if w_ld_dir.exists():
                self.w_file = w_ld_dir / "weights."
            else:
                raise ValueError(
                    "No w_file provided and no weights found in generate_ldscore output."
                )
        self.w_file = Path(self.w_file)

        if self.mkscore_feather_path is None:
            self.mkscore_feather_path = (
                Path(self.workdir)
                / self.sample_name
                / "latent_to_gene"
                / f"{self.sample_name}_gene_marker_score.feather"
            )
        else:
            self.mkscore_feather_path = Path(self.mkscore_feather_path)

        if self.ldscore_save_format == "quick_mode":
            if self.snp_gene_weight_adata_path is None:
                raise ValueError(
                    "snp_gene_weight_adata_path must be provided when ldscore_save_format is quick_mode."
                )
            self.snp_gene_weight_adata_path = Path(self.snp_gene_weight_adata_path)

        self.process_additional_baseline_annotation()

    def process_additional_baseline_annotation(self) -> None:
        """Disable extra baseline annotations when they are not present."""

        additional_baseline_dir = self.ldscore_save_dir / "additional_baseline"
        if not additional_baseline_dir.exists():
            self.use_additional_baseline_annotation = False
            return

        for chrom in range(1, 23):
            baseline_path = additional_baseline_dir / f"baseline.{chrom}.l2.ldscore.feather"
            if not baseline_path.exists():
                raise FileNotFoundError(
                    f"{baseline_path} is required when additional baseline annotations are enabled."
                )


@dataclass
class CauchyCombinationConfig:
    """Configuration for the vendored gsMap cauchy-combination step."""

    workdir: str
    trait_name: str
    annotation: str
    sample_name: str | None = None
    sample_name_list: list[str] | None = None
    output_file: str | Path | None = None

    @property
    def cauchy_save_dir(self) -> Path:
        """Return the output directory for cauchy-combination results."""

        if self.sample_name is None:
            return Path(self.workdir)
        return Path(self.workdir) / self.sample_name / "cauchy_combination"

    @property
    def ldsc_save_dir(self) -> Path:
        """Return the directory holding spatial-LDSC outputs."""

        return Path(self.workdir) / self.sample_name / "spatial_ldsc"

    @property
    def hdf5_with_latent_path(self) -> Path:
        """Return the latent-augmented h5ad used to recover annotations."""

        return (
            Path(self.workdir)
            / self.sample_name
            / "find_latent_representations"
            / f"{self.sample_name}_add_latent.h5ad"
        )

    def get_ldsc_result_file(self, trait_name: str) -> Path:
        """Return the spatial-LDSC result file for one trait."""

        return self.ldsc_save_dir / f"{self.sample_name}_{trait_name}.csv.gz"

    def get_cauchy_result_file(self, trait_name: str) -> Path:
        """Return the cauchy-combination result file for one trait."""

        return self.cauchy_save_dir / f"{self.sample_name}_{trait_name}.Cauchy.csv.gz"

    def __post_init__(self) -> None:
        """Normalize sample-name inputs and derive the default output path."""

        if self.sample_name_list is None:
            self.sample_name_list = []

        if self.sample_name is not None:
            if self.sample_name_list:
                raise ValueError("Only one of sample_name and sample_name_list must be provided.")
            self.sample_name_list = [self.sample_name]
            if self.output_file is None:
                self.output_file = self.get_cauchy_result_file(self.trait_name)
        else:
            if not self.sample_name_list:
                raise ValueError("At least one sample name must be provided.")
            if self.output_file is None:
                raise ValueError(
                    "output_file must be provided when sample_name_list is used without sample_name."
                )

        self.output_file = Path(self.output_file)


@dataclass
class DiagnosisConfig:
    """Configuration for vendored gsMap diagnosis plots and tables."""

    workdir: str
    sample_name: str
    annotation: str
    trait_name: str
    sumstats_file: str
    plot_type: str = "all"
    top_corr_genes: int = 50
    selected_genes: list[str] | None = None
    fig_width: int | None = None
    fig_height: int | None = None
    point_size: int | None = None
    fig_style: str = "light"

    @property
    def hdf5_with_latent_path(self) -> Path:
        """Return the latent-augmented h5ad used by the report diagnostics."""

        return (
            Path(self.workdir)
            / self.sample_name
            / "find_latent_representations"
            / f"{self.sample_name}_add_latent.h5ad"
        )

    @property
    def mkscore_feather_path(self) -> Path:
        """Return the latent-to-gene feather file used by the report diagnostics."""

        return (
            Path(self.workdir)
            / self.sample_name
            / "latent_to_gene"
            / f"{self.sample_name}_gene_marker_score.feather"
        )

    @property
    def ldscore_save_dir(self) -> Path:
        """Return the generate-ldscore directory."""

        return Path(self.workdir) / self.sample_name / "generate_ldscore"

    @property
    def ldsc_save_dir(self) -> Path:
        """Return the spatial-LDSC output directory."""

        return Path(self.workdir) / self.sample_name / "spatial_ldsc"

    @property
    def cauchy_save_dir(self) -> Path:
        """Return the cauchy-combination output directory."""

        return Path(self.workdir) / self.sample_name / "cauchy_combination"

    def get_report_dir(self, trait_name: str) -> Path:
        """Return the report directory for one trait."""

        return Path(self.workdir) / self.sample_name / "report" / trait_name

    def get_gsmap_report_file(self, trait_name: str) -> Path:
        """Return the final HTML report path for one trait."""

        return self.get_report_dir(trait_name) / f"{self.sample_name}_{trait_name}_gsMap_Report.html"

    def get_manhattan_html_plot_path(self, trait_name: str) -> Path:
        """Return the Manhattan HTML path for one trait."""

        return (
            self.get_report_dir(trait_name)
            / "manhattan_plot"
            / f"{self.sample_name}_{trait_name}_Diagnostic_Manhattan_Plot.html"
        )

    def get_gss_plot_dir(self, trait_name: str) -> Path:
        """Return the GSS plot directory for one trait."""

        return self.get_report_dir(trait_name) / "GSS_plot"

    def get_gss_plot_select_gene_file(self, trait_name: str) -> Path:
        """Return the selected-gene list file for the GSS plots."""

        return self.get_gss_plot_dir(trait_name) / "plot_genes.csv"

    def get_ldsc_result_file(self, trait_name: str) -> Path:
        """Return the spatial-LDSC CSV path for one trait."""

        return self.ldsc_save_dir / f"{self.sample_name}_{trait_name}.csv.gz"

    def get_cauchy_result_file(self, trait_name: str) -> Path:
        """Return the cauchy-combination CSV path for one trait."""

        return self.cauchy_save_dir / f"{self.sample_name}_{trait_name}.Cauchy.csv.gz"

    def get_gene_diagnostic_info_save_path(self, trait_name: str) -> Path:
        """Return the gene-diagnostic info CSV path for one trait."""

        return (
            self.get_report_dir(trait_name)
            / f"{self.sample_name}_{trait_name}_Gene_Diagnostic_Info.csv"
        )

    def get_gsmap_plot_save_dir(self, trait_name: str) -> Path:
        """Return the directory holding the gsMap spatial plot files."""

        return self.get_report_dir(trait_name) / "gsMap_plot"

    def get_gsmap_html_plot_save_path(self, trait_name: str) -> Path:
        """Return the interactive gsMap spatial-plot HTML path."""

        return self.get_gsmap_plot_save_dir(trait_name) / f"{self.sample_name}_{trait_name}_gsMap_plot.html"

    def __post_init__(self) -> None:
        """Validate figure customization arguments and required inputs."""

        if not Path(self.sumstats_file).exists():
            raise FileNotFoundError(f"{self.sumstats_file} does not exist.")

        if any(value is not None for value in [self.fig_width, self.fig_height, self.point_size]):
            if not all(value is not None for value in [self.fig_width, self.fig_height, self.point_size]):
                raise ValueError(
                    "fig_width, fig_height, and point_size must be provided together."
                )
            self.customize_fig = True
        else:
            self.customize_fig = False


@dataclass
class ReportConfig(DiagnosisConfig):
    """Configuration for vendored gsMap HTML report generation."""
