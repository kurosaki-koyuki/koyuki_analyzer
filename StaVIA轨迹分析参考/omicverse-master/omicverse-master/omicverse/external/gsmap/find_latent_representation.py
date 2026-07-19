from __future__ import annotations

"""Vendored gsMap latent-representation workflow for OmicVerse."""

import logging
import random

import numpy as np
import scanpy as sc
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
from sklearn.decomposition import PCA
from sklearn.preprocessing import LabelEncoder

from ._config import FindLatentRepresentationsConfig
from ._style import Colors, EMOJI
from .gnn.adjacency_matrix import construct_adjacency_matrix
from .gnn.train import model_trainer

logger = logging.getLogger(__name__)


def set_seed(seed_value: int) -> None:
    """Set random seeds for reproducible latent-representation training."""

    if not _TORCH_AVAILABLE:
        raise ImportError(
            "torch is required for gsMap. "
            "Install with: pip install omicverse[gsmap]"
        )
    torch.manual_seed(seed_value)
    np.random.seed(seed_value)
    random.seed(seed_value)
    if torch.cuda.is_available():
        print(f"{EMOJI['gpu']} {Colors.GREEN}Using GPU for computations.{Colors.ENDC}")
        torch.cuda.manual_seed(seed_value)
        torch.cuda.manual_seed_all(seed_value)
    else:
        print(f"{EMOJI['cpu']} {Colors.GREEN}Using CPU for computations.{Colors.ENDC}")


def preprocess_data(adata, params: FindLatentRepresentationsConfig):
    """Preprocess the AnnData object before latent learning."""

    print(f"{EMOJI['start']} {Colors.CYAN}Preprocessing data...{Colors.ENDC}")
    adata.var_names_make_unique()

    if params.data_layer in adata.layers:
        print(f"{Colors.BLUE}    Using data layer: {params.data_layer}{Colors.ENDC}")
        adata.X = adata.layers[params.data_layer].copy()
    elif params.data_layer == "X":
        print(f"{Colors.BLUE}    Using data layer: X{Colors.ENDC}")
        if adata.X.dtype == "float32" or adata.X.dtype == "float64":
            print(
                f"{Colors.WARNING}⚠️  The data layer should be raw count data.{Colors.ENDC}"
            )
    else:
        raise ValueError(
            f"Invalid data layer: {params.data_layer}, please check the input data."
        )

    if hasattr(adata.X, "astype"):
        adata.X = adata.X.astype(np.float32)

    if params.data_layer in ["count", "counts", "X"]:
        print(f"{Colors.CYAN}Begin highly variable gene selection{Colors.ENDC}")
        try:
            sc.pp.highly_variable_genes(
                adata,
                flavor="seurat_v3",
                n_top_genes=params.feat_cell,
            )
        except ValueError as exc:
            print(
                f"{Colors.WARNING}⚠️  seurat_v3 highly_variable_genes failed with {exc}. "
                f"Falling back to the seurat flavor.{Colors.ENDC}"
            )
            sc.pp.highly_variable_genes(
                adata,
                flavor="seurat",
                n_top_genes=params.feat_cell,
            )

        if params.pearson_residuals:
            pearson_residuals = sc.experimental.pp.normalize_pearson_residuals(
                adata,
                inplace=False,
                clip=10,
            )
            adata.layers["pearson_residuals"] = pearson_residuals["X"]

        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
    else:
        sc.pp.highly_variable_genes(adata, flavor="seurat", n_top_genes=params.feat_cell)

    return adata


class latent_representation_finder:
    """Compute latent representations with the vendored gsMap GNN stack."""

    def __init__(self, adata, args: FindLatentRepresentationsConfig) -> None:
        self.params = args

        if "pearson_residuals" in adata.layers:
            self.expression_array = (
                adata[:, adata.var.highly_variable].layers["pearson_residuals"].copy()
            )
        else:
            self.expression_array = adata[:, adata.var.highly_variable].X.copy()
            self.expression_array = sc.pp.scale(self.expression_array, max_value=10)

        self.graph_dict = construct_adjacency_matrix(adata, self.params)
        self.latent_pca = None

    def compute_pca(self) -> np.ndarray:
        """Compute PCA features used as optional GNN input."""

        self.latent_pca = PCA(n_components=self.params.n_comps).fit_transform(
            self.expression_array
        )
        return self.latent_pca

    def run_gnn_vae(self, label, verbose: str = "whole ST data") -> np.ndarray:
        """Train the graph attention autoencoder and return latent embeddings."""

        if self.params.input_pca:
            node_x = self.compute_pca()
        else:
            node_x = self.expression_array

        self.params.n_nodes = node_x.shape[0]
        self.params.feat_cell = node_x.shape[1]

        print(f"{EMOJI['start']} {Colors.CYAN}Finding latent representations for {verbose}...{Colors.ENDC}")
        gvae = model_trainer(node_x, self.graph_dict, self.params, label)
        gvae.run_train()

        del self.graph_dict
        return gvae.get_latent()


def run_find_latent_representation(args: FindLatentRepresentationsConfig):
    """Run the vendored gsMap latent-representation workflow and save the result."""

    set_seed(2024)

    print(f"{EMOJI['start']} {Colors.CYAN}Loading ST data of {args.sample_name}...{Colors.ENDC}")
    adata = sc.read_h5ad(args.input_hdf5_path)
    sc.pp.filter_genes(adata, min_cells=1)
    print(
        f"{Colors.BLUE}    The ST data contains {adata.shape[0]} cells, {adata.shape[1]} genes.{Colors.ENDC}"
    )

    if args.annotation is not None:
        adata = adata[~adata.obs[args.annotation].isnull()]
        annotation_counts = adata.obs[args.annotation].value_counts()
        valid_annotations = annotation_counts[annotation_counts >= 30].index.to_list()
        adata = adata[adata.obs[args.annotation].isin(valid_annotations)]

        label_encoder = LabelEncoder()
        label = label_encoder.fit_transform(adata.obs[args.annotation])
    else:
        label = None

    adata = preprocess_data(adata, args)

    latent_rep = latent_representation_finder(adata, args)
    latent_gvae = latent_rep.run_gnn_vae(label)
    latent_pca = latent_rep.latent_pca

    print(f"{EMOJI['done']} {Colors.GREEN}Adding latent representations...{Colors.ENDC}")
    adata.obsm["latent_GVAE"] = latent_gvae
    adata.obsm["latent_PCA"] = latent_pca

    output_path = args.hdf5_with_latent_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"{EMOJI['done']} {Colors.GREEN}Saving ST data to {output_path}{Colors.ENDC}")
    adata.write(output_path)
    return output_path
