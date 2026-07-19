from __future__ import annotations

"""Vendored gsMap latent-to-gene workflow for OmicVerse."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
import scipy
from scipy.stats import gmean, rankdata
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
from tqdm.auto import tqdm, trange

from ._config import LatentToGeneConfig
from ._style import Colors, EMOJI

logger = logging.getLogger(__name__)


def find_neighbors(coor, num_neighbour: int) -> pd.DataFrame:
    """Find spatial nearest neighbors for each cell or spot."""

    neighbors = NearestNeighbors(n_neighbors=num_neighbour).fit(coor)
    distances, indices = neighbors.kneighbors(coor, return_distance=True)
    cell_indices = np.arange(coor.shape[0])
    cell1 = np.repeat(cell_indices, indices.shape[1])
    cell2 = indices.flatten()
    distance = distances.flatten()
    return pd.DataFrame({"cell1": cell1, "cell2": cell2, "distance": distance})


def build_spatial_net(adata, annotation: str | None, num_neighbour: int) -> dict[int, np.ndarray]:
    """Build the spatial neighborhood dictionary used by latent-to-gene."""

    print(f"{EMOJI['start']} {Colors.CYAN}Building spatial graph based on spatial coordinates...{Colors.ENDC}")

    coor = adata.obsm["spatial"]
    if annotation is not None:
        print(f"{Colors.BLUE}    Cell annotations are provided.{Colors.ENDC}")
        spatial_net_list = []
        for cell_type in adata.obs[annotation].dropna().unique():
            idx = np.where(adata.obs[annotation] == cell_type)[0]
            coor_temp = coor[idx, :]
            spatial_net_temp = find_neighbors(coor_temp, min(num_neighbour, coor_temp.shape[0]))
            spatial_net_temp["cell1"] = idx[spatial_net_temp["cell1"].values]
            spatial_net_temp["cell2"] = idx[spatial_net_temp["cell2"].values]
            spatial_net_list.append(spatial_net_temp)
            print(f"{Colors.BLUE}    {cell_type}: {coor_temp.shape[0]} cells{Colors.ENDC}")

        if pd.isnull(adata.obs[annotation]).any():
            idx_nan = np.where(pd.isnull(adata.obs[annotation]))[0]
            print(f"{Colors.BLUE}    NaN: {len(idx_nan)} cells{Colors.ENDC}")
            spatial_net_temp = find_neighbors(coor, num_neighbour)
            spatial_net_temp = spatial_net_temp[spatial_net_temp["cell1"].isin(idx_nan)]
            spatial_net_list.append(spatial_net_temp)

        spatial_net = pd.concat(spatial_net_list, axis=0)
    else:
        print(f"{Colors.BLUE}    Cell annotations are not provided.{Colors.ENDC}")
        spatial_net = find_neighbors(coor, num_neighbour)

    return spatial_net.groupby("cell1")["cell2"].apply(np.array).to_dict()


def find_neighbors_regional(
    cell_pos: int,
    spatial_net_dict: dict[int, np.ndarray],
    coor_latent: np.ndarray,
    config: LatentToGeneConfig,
    cell_annotations,
):
    """Select latent-space neighbors within a spatial neighborhood."""

    cell_use_pos = spatial_net_dict.get(cell_pos, [])
    if len(cell_use_pos) == 0:
        return []

    cell_latent = coor_latent[cell_pos, :].reshape(1, -1)
    neighbors_latent = coor_latent[cell_use_pos, :]
    similarity = cosine_similarity(cell_latent, neighbors_latent).reshape(-1)

    if config.annotation is not None:
        cell_annotation = cell_annotations[cell_pos]
        neighbor_annotations = cell_annotations[cell_use_pos]
        mask = neighbor_annotations == cell_annotation
        if not np.any(mask):
            return []
        similarity = similarity[mask]
        cell_use_pos = cell_use_pos[mask]

    if len(similarity) == 0:
        return []

    indices = np.argsort(-similarity)
    top_indices = indices[: config.num_neighbour]
    return cell_use_pos[top_indices]


def compute_regional_mkscore(
    cell_pos: int,
    spatial_net_dict: dict[int, np.ndarray],
    coor_latent: np.ndarray,
    config: LatentToGeneConfig,
    cell_annotations,
    ranks: np.ndarray,
    frac_whole: np.ndarray,
    adata_x_bool,
    pearson_residuals: bool,
) -> np.ndarray:
    """Compute marker scores for one focal region."""

    cell_select_pos = find_neighbors_regional(
        cell_pos,
        spatial_net_dict,
        coor_latent,
        config,
        cell_annotations,
    )
    if len(cell_select_pos) == 0:
        return np.zeros(ranks.shape[1], dtype=np.float16)

    ranks_tg = ranks[cell_select_pos, :]
    gene_ranks_region = gmean(ranks_tg, axis=0)
    gene_ranks_region[gene_ranks_region <= 1] = 0

    if not config.no_expression_fraction:
        frac_focal = adata_x_bool[cell_select_pos, :].sum(axis=0).A1 / len(cell_select_pos)
        frac_region = frac_focal / frac_whole
        frac_region[frac_region <= 1] = 0
        frac_region[frac_region > 1] = 1
        gene_ranks_region = gene_ranks_region * frac_region

    mk_score = np.exp(gene_ranks_region) - 1 if not pearson_residuals else gene_ranks_region
    return mk_score.astype(np.float16, copy=False)


def run_latent_to_gene(config: LatentToGeneConfig):
    """Run the vendored gsMap latent-to-gene workflow and save marker scores."""

    if not config.hdf5_with_latent_path.exists():
        raise FileNotFoundError(
            f"{config.hdf5_with_latent_path} does not exist. "
            "Run find_latent_representation first."
        )

    print(f"{EMOJI['start']} {Colors.CYAN}Loading the spatial data...{Colors.ENDC}")
    adata = sc.read_h5ad(config.hdf5_with_latent_path)
    print(f"{Colors.BLUE}    Loaded spatial data with {adata.n_obs} cells and {adata.n_vars} genes.{Colors.ENDC}")

    if config.annotation is not None:
        print(f"{EMOJI['start']} {Colors.CYAN}Cell annotations are provided as {config.annotation}...{Colors.ENDC}")
        initial_cell_count = adata.n_obs
        adata = adata[~pd.isnull(adata.obs[config.annotation]), :]
        logger.info(
            "Removed null annotations. Cells retained: %s (initial: %s).",
            adata.n_obs,
            initial_cell_count,
        )

    # Homologs transformation (matching upstream gsMap behaviour)
    if config.homolog_file is not None and config.species is not None:
        species_col_name = f"{config.species}_homolog"
        if species_col_name in adata.var.columns:
            logger.warning(
                "Column '%s' already exists in adata.var. Skipping homolog transformation.",
                species_col_name,
            )
        else:
            print(f"{EMOJI['start']} {Colors.CYAN}Transforming {config.species} to HUMAN_GENE_SYM...{Colors.ENDC}")
            homologs = pd.read_csv(config.homolog_file, sep="\t")
            if homologs.shape[1] != 2:
                raise ValueError(
                    "Homologs file must have two columns: one for the species and one for the human gene symbol."
                )
            homologs.columns = [config.species, "HUMAN_GENE_SYM"]
            homologs.set_index(config.species, inplace=True)

            adata = adata[:, adata.var_names.isin(homologs.index)]
            print(f"{Colors.BLUE}    {adata.shape[1]} genes retained after homolog transformation.{Colors.ENDC}")
            if adata.shape[1] < 100:
                raise ValueError("Too few genes retained in ST data (<100).")

            gene_mapping = pd.Series(
                homologs.loc[adata.var_names, "HUMAN_GENE_SYM"].values, index=adata.var_names
            )
            adata.var[species_col_name] = adata.var_names.values
            adata.var_names = gene_mapping.values
            adata.var.index.name = "HUMAN_GENE_SYM"

            adata = adata[:, ~adata.var_names.duplicated()]
            print(f"{Colors.BLUE}    {adata.shape[1]} genes retained after removing duplicates.{Colors.ENDC}")

    if config.annotation is not None:
        cell_annotations = adata.obs[config.annotation].values
    else:
        cell_annotations = None

    print(f"{EMOJI['start']} {Colors.CYAN}Building the spatial graph...{Colors.ENDC}")
    spatial_net_dict = build_spatial_net(adata, config.annotation, config.num_neighbour_spatial)
    print(f"{EMOJI['done']} {Colors.GREEN}Spatial graph built successfully.{Colors.ENDC}")

    print(f"{EMOJI['start']} {Colors.CYAN}Extracting the latent representation...{Colors.ENDC}")
    coor_latent = adata.obsm[config.latent_representation].astype(np.float32)
    print(f"{EMOJI['done']} {Colors.GREEN}Latent representation extracted.{Colors.ENDC}")

    print(f"{EMOJI['start']} {Colors.CYAN}Ranking the spatial data...{Colors.ENDC}")
    if not scipy.sparse.issparse(adata.X):
        adata_x = scipy.sparse.csr_matrix(adata.X)
    elif isinstance(adata.X, scipy.sparse.csr_matrix):
        adata_x = adata.X
    else:
        adata_x = adata.X.tocsr()

    n_cells = adata.n_obs
    n_genes = adata.n_vars
    pearson_residuals = "pearson_residuals" in adata.layers
    ranks = np.zeros((n_cells, adata.n_vars), dtype=np.float16)

    if pearson_residuals:
        print(f"{Colors.BLUE}    Using pearson residuals for ranking.{Colors.ENDC}")
        data = adata.layers["pearson_residuals"]
        for i in tqdm(range(n_cells), desc="Computing ranks per cell", leave=True):
            ranks[i, :] = rankdata(data[i, :], method="average")
    else:
        for i in tqdm(range(n_cells), desc="Computing ranks per cell", leave=True):
            data = adata_x[i, :].toarray().flatten()
            ranks[i, :] = rankdata(data, method="average")

    gM = gmean(ranks, axis=0).astype(np.float16)
    adata_x_bool = adata_x.astype(bool)
    frac_whole = np.asarray(adata_x_bool.sum(axis=0)).flatten() / n_cells
    print(f"{EMOJI['done']} {Colors.GREEN}Gene expression proportion of each gene across cells computed.{Colors.ENDC}")

    frac_whole += 1e-12
    ranks /= gM

    print(f"{EMOJI['start']} {Colors.CYAN}Computing marker scores...{Colors.ENDC}")
    mk_score = np.zeros((n_cells, n_genes), dtype=np.float16)
    for cell_pos in trange(n_cells, desc="Calculating marker scores"):
        mk_score[cell_pos, :] = compute_regional_mkscore(
            cell_pos,
            spatial_net_dict,
            coor_latent,
            config,
            cell_annotations,
            ranks,
            frac_whole,
            adata_x_bool,
            pearson_residuals,
        )

    mk_score = mk_score.T
    print(f"{EMOJI['done']} {Colors.GREEN}Marker scores computed.{Colors.ENDC}")

    gene_names = adata.var_names.values.astype(str)
    mt_gene_mask = ~(
        np.char.startswith(gene_names, "MT-") | np.char.startswith(gene_names, "mt-")
    )
    mk_score = mk_score[mt_gene_mask, :]
    gene_names = gene_names[mt_gene_mask]
    print(f"{Colors.BLUE}    Removed mitochondrial genes. Remaining genes: {len(gene_names)}.{Colors.ENDC}")

    print(f"{EMOJI['start']} {Colors.CYAN}Saving marker scores...{Colors.ENDC}")
    output_file_path = Path(config.mkscore_feather_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    mk_score_df = pd.DataFrame(mk_score, index=gene_names, columns=adata.obs_names)
    mk_score_df.reset_index(inplace=True)
    mk_score_df.rename(columns={"index": "HUMAN_GENE_SYM"}, inplace=True)
    mk_score_df.to_feather(output_file_path)
    print(f"{EMOJI['done']} {Colors.GREEN}Marker scores saved to {output_file_path}.{Colors.ENDC}")

    adata.write(config.hdf5_with_latent_path)
    print(f"{EMOJI['done']} {Colors.GREEN}Modified adata object saved to {config.hdf5_with_latent_path}.{Colors.ENDC}")
    return output_file_path
