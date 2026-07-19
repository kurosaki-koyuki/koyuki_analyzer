from __future__ import annotations

"""Adjacency helpers for the vendored gsMap latent-representation workflow."""

import numpy as np
import pandas as pd
import scipy.sparse as sp
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
from sklearn.neighbors import NearestNeighbors

from .._style import Colors, EMOJI


def cal_spatial_net(adata, n_neighbors: int = 5, verbose: bool = True) -> pd.DataFrame:
    """Construct the spatial neighbor network from ``adata.obsm['spatial']``."""

    if verbose:
        print(f"{EMOJI['start']} {Colors.CYAN}Calculating spatial graph...{Colors.ENDC}")

    coordinates = pd.DataFrame(adata.obsm["spatial"], index=adata.obs.index)
    neighbors = NearestNeighbors(n_neighbors=n_neighbors).fit(coordinates)
    distances, indices = neighbors.kneighbors(coordinates)

    n_cells, n_neighbors = indices.shape
    cell_indices = np.arange(n_cells)
    cell1 = np.repeat(cell_indices, n_neighbors)
    cell2 = indices.flatten()
    distance = distances.flatten()

    knn_df = pd.DataFrame({"cell1": cell1, "cell2": cell2, "distance": distance})
    knn_df = knn_df[knn_df["distance"] > 0].copy()

    cell_id_map = dict(zip(cell_indices, coordinates.index, strict=False))
    knn_df["cell1"] = knn_df["cell1"].map(cell_id_map)
    knn_df["cell2"] = knn_df["cell2"].map(cell_id_map)
    return knn_df


def sparse_mx_to_torch_sparse_tensor(sparse_mx):
    """Convert a scipy sparse matrix into a torch sparse COO tensor."""

    if not _TORCH_AVAILABLE:
        raise ImportError(
            "torch is required for gsMap. "
            "Install with: pip install omicverse[gsmap]"
        )
    sparse_mx = sparse_mx.tocoo().astype(np.float32)
    indices = torch.from_numpy(np.vstack((sparse_mx.row, sparse_mx.col)).astype(np.int64))
    values = torch.from_numpy(sparse_mx.data)
    shape = torch.Size(sparse_mx.shape)
    return torch.sparse_coo_tensor(indices, values, shape)


def preprocess_graph(adj):
    """Symmetrically normalize the adjacency matrix."""

    adj = sp.coo_matrix(adj)
    adj_plus_identity = adj + sp.eye(adj.shape[0])
    row_sum = np.array(adj_plus_identity.sum(1)).flatten()
    degree_mat_inv_sqrt = sp.diags(np.power(row_sum, -0.5))
    adj_normalized = (
        adj_plus_identity.dot(degree_mat_inv_sqrt)
        .transpose()
        .dot(degree_mat_inv_sqrt)
        .tocoo()
    )
    return sparse_mx_to_torch_sparse_tensor(adj_normalized)


def construct_adjacency_matrix(adata, params, verbose: bool = True) -> dict[str, object]:
    """Construct weighted or unweighted adjacency matrices from spatial coordinates."""

    spatial_net = cal_spatial_net(adata, n_neighbors=params.n_neighbors, verbose=verbose)
    if verbose:
        num_edges = spatial_net.shape[0]
        num_cells = adata.n_obs
        print(f"{Colors.BLUE}    The graph contains {num_edges} edges, {num_cells} cells.{Colors.ENDC}")
        print(f"{Colors.BLUE}    {num_edges / num_cells:.2f} neighbors per cell on average.{Colors.ENDC}")

    cell_ids = {cell: idx for idx, cell in enumerate(adata.obs.index)}
    spatial_net["cell1"] = spatial_net["cell1"].map(cell_ids)
    spatial_net["cell2"] = spatial_net["cell2"].map(cell_ids)

    if params.weighted_adj:
        distance_normalized = spatial_net["distance"] / (spatial_net["distance"].max() + 1)
        weights = np.exp(-0.5 * distance_normalized**2)
        adj_org = sp.coo_matrix(
            (weights, (spatial_net["cell1"], spatial_net["cell2"])),
            shape=(adata.n_obs, adata.n_obs),
        )
    else:
        adj_org = sp.coo_matrix(
            (
                np.ones(spatial_net.shape[0]),
                (spatial_net["cell1"], spatial_net["cell2"]),
            ),
            shape=(adata.n_obs, adata.n_obs),
        )

    adj_norm = preprocess_graph(adj_org)
    norm_value = adj_org.shape[0] ** 2 / ((adj_org.shape[0] ** 2 - adj_org.sum()) * 2)
    return {"adj_org": adj_org, "adj_norm": adj_norm, "norm_value": norm_value}
