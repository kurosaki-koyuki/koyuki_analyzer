from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import FancyArrowPatch
import numpy as np
import pandas as pd
import pytest
import anndata as ad
from scipy import sparse

import omicverse as ov
from omicverse.pl import _trajectory as trajectory_mod
from omicverse.single import Monocle


@pytest.fixture(scope="module")
def ordered_mono():
    rng = np.random.default_rng(42)
    n_cells, n_genes = 150, 80
    X = rng.poisson(5.0, (n_cells, n_genes)).astype(np.float64)
    X[:50, :30] += rng.poisson(10.0, (50, 30)).astype(np.float64)
    X[100:, 30:60] += rng.poisson(10.0, (50, 30)).astype(np.float64)
    obs = pd.DataFrame(
        {"group": ["A"] * 50 + ["Trunk"] * 50 + ["B"] * 50},
        index=[f"c{i}" for i in range(n_cells)],
    )
    var = pd.DataFrame(
        {"gene_short_name": [f"g{i}" for i in range(n_genes)]},
        index=[f"g{i}" for i in range(n_genes)],
    )
    mono = Monocle(ad.AnnData(X=X, obs=obs, var=var))
    (mono.preprocess().select_ordering_genes().reduce_dimension().order_cells())
    return mono


def _mono_with_collapsed_first_two_branch_points(ordered_mono):
    if len(ordered_mono.branch_points) < 2:
        pytest.skip("Need at least two branch points for label-overlap test")
    mono = Monocle(ordered_mono.adata.copy())
    monocle = mono.adata.uns["monocle"]
    mst_names = monocle["mst"].vs["name"]
    first = mst_names.index(monocle["branch_points"][0])
    second = mst_names.index(monocle["branch_points"][1])
    reduced = np.asarray(monocle["reducedDimK"]).copy()
    reduced[:, second] = reduced[:, first]
    monocle["reducedDimK"] = reduced
    return mono


def _branch_label_centers_px(fig, ax):
    fig.canvas.draw()
    texts = [text for text in ax.texts if text.get_text().isdigit()]
    centers = ax.transData.transform([text.get_position() for text in texts])
    return texts, centers


def _branch_label_connector_lines(ax):
    return [
        line for line in ax.lines
        if mcolors.same_color(line.get_color(), "#C8C8C8")
    ]


def test_trajectory_draws_monocle_backbone_with_ov_style(ordered_mono):
    fig, ax = ov.pl.trajectory(
        ordered_mono.adata,
        method="monocle",
        basis="X_DDRTree",
        color="State",
    )
    assert fig.get_size_inches()[0] == pytest.approx(5)
    assert fig.get_size_inches()[1] == pytest.approx(4)
    assert ax.get_title() == "State"
    assert ax.lines
    assert mcolors.same_color(ax.lines[0].get_color(), "#8A8A8A")
    assert ax.lines[0].get_linewidth() == pytest.approx(1.15)
    branch_collections = [
        collection
        for collection in ax.collections
        if len(collection.get_sizes())
        and collection.get_sizes()[0] == pytest.approx(150)
    ]
    assert branch_collections
    expected_labels = [str(i + 1) for i in range(len(ordered_mono.branch_points))]
    branch_labels = [text.get_text() for text in ax.texts if text.get_text().isdigit()]
    assert branch_labels == expected_labels
    plt.close(fig)


def test_trajectory_overlay_draws_on_existing_embedding_axis(ordered_mono):
    fig, ax = plt.subplots(figsize=(4, 4))
    ov.pl.embedding(
        ordered_mono.adata,
        basis="X_DDRTree",
        color="State",
        ax=ax,
        show=False,
        size=50,
    )
    ov.pl.trajectory_overlay(ordered_mono.adata, ax=ax, method="monocle")
    assert ax.lines
    assert mcolors.same_color(ax.lines[0].get_color(), "#8A8A8A")
    assert ax.lines[0].get_linewidth() == pytest.approx(1.25)
    branch_labels = [text for text in ax.texts if text.get_text().isdigit()]
    assert branch_labels
    assert all(text.get_fontsize() == pytest.approx(10) for text in branch_labels)
    plt.close(fig)


def test_branch_labels_stay_in_place_when_not_overlapping():
    fig, ax = plt.subplots()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    fig.canvas.draw()
    anchors = np.array([[1.0, 1.0], [9.0, 9.0]])
    positions, moved = trajectory_mod._resolve_branch_label_positions(
        ax,
        anchors,
        size=150,
        fontsize=10,
    )
    assert not moved.any()
    assert np.allclose(positions, anchors)
    plt.close(fig)


def test_trajectory_adjusts_only_overlapping_branch_labels(ordered_mono):
    mono = _mono_with_collapsed_first_two_branch_points(ordered_mono)
    fig, ax = ov.pl.trajectory(
        mono.adata,
        method="monocle",
        basis="X_DDRTree",
        color="State",
    )
    texts, centers = _branch_label_centers_px(fig, ax)
    assert [text.get_text() for text in texts[:2]] == ["1", "2"]
    assert np.linalg.norm(centers[0] - centers[1]) > 60
    connectors = _branch_label_connector_lines(ax)
    assert connectors
    assert connectors[0].get_linewidth() == pytest.approx(0.7)
    assert connectors[0].get_alpha() == pytest.approx(0.85)
    plt.close(fig)


def test_trajectory_tree_uses_pseudotime_and_branch_labels(ordered_mono):
    fig, ax = ov.pl.trajectory_tree(
        ordered_mono.adata,
        method="monocle",
        color="State",
    )
    assert fig.get_size_inches()[0] == pytest.approx(5)
    assert fig.get_size_inches()[1] == pytest.approx(4)
    assert ax.get_xlabel() == ""
    assert ax.get_ylabel() == "Pseudotime"
    assert ax.lines
    assert mcolors.same_color(ax.lines[0].get_color(), "#8A8A8A")
    assert ax.lines[0].get_linewidth() == pytest.approx(0.7)
    cell_y = ax.collections[0].get_offsets()[:, 1]
    pseudotime = ordered_mono.adata.obs["Pseudotime"].to_numpy(dtype=float)
    assert np.allclose(cell_y, pseudotime)
    assert ax.yaxis_inverted()
    expected_labels = [str(i + 1) for i in range(len(ordered_mono.branch_points))]
    branch_labels = [text.get_text() for text in ax.texts if text.get_text().isdigit()]
    assert branch_labels == expected_labels
    plt.close(fig)


def test_trajectory_tree_can_hide_branch_labels(ordered_mono):
    fig, ax = ov.pl.trajectory_tree(
        ordered_mono.adata,
        method="monocle",
        color="State",
        show_branch_points=False,
    )
    branch_labels = [text.get_text() for text in ax.texts if text.get_text().isdigit()]
    assert branch_labels == []
    plt.close(fig)


def test_trajectory_overlay_supports_paga_graph():
    adata = ad.AnnData(
        X=np.ones((6, 2)),
        obs=pd.DataFrame(
            {
                "clusters": pd.Categorical(
                    ["A", "A", "B", "B", "C", "C"],
                    categories=["A", "B", "C"],
                )
            },
            index=[f"c{i}" for i in range(6)],
        ),
    )
    adata.obsm["X_umap"] = np.array(
        [[0, 0], [0, 1], [2, 0], [2, 1], [4, 0], [4, 1]],
        dtype=float,
    )
    adata.uns["paga"] = {
        "groups": "clusters",
        "connectivities_tree": sparse.csr_matrix(
            np.array(
                [
                    [0, 1, 0],
                    [1, 0, 1],
                    [0, 1, 0],
                ],
                dtype=float,
            )
        ),
    }
    fig, ax = plt.subplots()
    ax.scatter(adata.obsm["X_umap"][:, 0], adata.obsm["X_umap"][:, 1])
    ov.pl.trajectory_overlay(
        adata,
        ax=ax,
        method="paga",
        show_branch_points=False,
    )
    assert len(ax.lines) == 2
    assert all(mcolors.same_color(line.get_color(), "#1A1A1A") for line in ax.lines)
    plt.close(fig)

    fig, ax = ov.pl.trajectory(
        adata,
        method="paga",
        groups="clusters",
        color="clusters",
    )
    assert fig.get_size_inches()[0] == pytest.approx(4)
    assert ax.lines
    assert all(mcolors.same_color(line.get_color(), "#1A1A1A") for line in ax.lines)
    plt.close(fig)

    fig, ax = ov.pl.trajectory_graph(
        adata,
        method="paga",
        groups="clusters",
        color="clusters",
        figsize=(4, 4),
    )
    assert tuple(fig.get_size_inches()) == pytest.approx((4, 4))
    assert ax.lines
    assert ax.collections
    plt.close(fig)

    fig, ax = ov.pl.trajectory_projection(
        adata,
        method="paga",
        groups="clusters",
        color="clusters",
    )
    assert fig.get_size_inches()[0] == pytest.approx(4)
    assert ax.lines
    assert ax.collections
    plt.close(fig)


def _make_stavia_stream_adata():
    adata = ad.AnnData(
        X=np.ones((4, 2)),
        obs=pd.DataFrame(
            {
                "clusters": pd.Categorical(
                    ["A", "A", "B", "B"],
                    categories=["A", "B"],
                )
            },
            index=[f"c{i}" for i in range(4)],
        ),
    )
    adata.obsm["X_umap"] = np.array(
        [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
        dtype=float,
    )
    adata.uns["clusters_colors"] = ["#111111", "#EEEEEE"]
    adata.uns["traj_stavia"] = {
        "method": "StaVIA",
        "basis": "X_umap",
        "cluster_key": "clusters",
        "params": {"RW2_mode": True},
    }
    return adata


class _FakeStaVIABackend:
    def __init__(self, adata):
        self.nsamples = adata.n_obs
        self.single_cell_pt_markov = np.linspace(0.0, 1.0, adata.n_obs)
        self.true_label = adata.obs["clusters"]
        self.labels = np.array([0, 0, 1, 1])
        self.single_cell_bp = np.array([[0.9], [0.8], [0.2], [0.1]], dtype=float)
        self.terminal_clusters = [1]
        self.root = [0]
        self.graph_node_pos = np.array([[0.0, 0.0], [1.0, 1.0]], dtype=float)
        self.edgelist = [(0, 1)]
        self.edgelist_maxout = [(0, 1)]
        self.markov_hitting_times = np.array([0.0, 1.0], dtype=float)
        self.knn = 5
        self.ncomp = 2
        self.time_series = False
        self.do_spatial_knn = False
        self.calls = []

    def _velocity_embedding(
        self,
        embedding,
        smooth_transition,
        b,
        use_sequentially_augmented=False,
    ):
        self.calls.append(
            {
                "embedding": embedding.copy(),
                "smooth_transition": smooth_transition,
                "b": b,
                "use_sequentially_augmented": use_sequentially_augmented,
            }
        )
        return np.array(
            [[1.0, 0.0], [1.0, 0.1], [0.1, 1.0], [0.0, 1.0]],
            dtype=float,
        )


def test_plot_stream_rejects_native_stavia_wrapper():
    adata = _make_stavia_stream_adata()
    raw_model = _FakeStaVIABackend(adata)

    class FakeStaVIA:
        def __init__(self):
            self.adata = adata
            self.model = raw_model
            self.basis = "X_umap"
            self.cluster_key = "clusters"

        def _effective_rw2_mode(self):
            return True

    with pytest.raises(ValueError, match="no longer wraps native StaVIA/VIA"):
        ov.pl.plot_stream(
            FakeStaVIA(),
            method="stavia",
            density_grid=0.3,
            n_neighbors_velocity_grid=2,
        )


def test_plot_stream_rejects_stavia_anndata_summary():
    adata = _make_stavia_stream_adata()

    with pytest.raises(ValueError, match="no longer wraps native StaVIA/VIA"):
        ov.pl.plot_stream(adata, method="stavia", key="traj_stavia")


def test_plot_stream_supports_generic_pseudotime_results():
    adata = _make_stavia_stream_adata()
    adata.obs["palantir_pseudotime"] = [0.0, 0.25, 0.75, 1.0]
    adata.obsp["connectivities"] = sparse.csr_matrix(
        np.array(
            [
                [0.0, 1.0, 1.0, 0.0],
                [1.0, 0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0, 1.0],
                [0.0, 1.0, 1.0, 0.0],
            ],
            dtype=float,
        )
    )

    fig, ax = ov.pl.plot_stream(
        adata,
        method="pseudotime",
        pseudotime_key="palantir_pseudotime",
        density_grid=0.3,
        color="clusters",
    )

    assert fig is ax.figure
    assert ax.collections
    plt.close(fig)


def test_stavia_native_plots_are_not_wrapped_in_ov_pl():
    adata = _make_stavia_stream_adata()
    raw_model = _FakeStaVIABackend(adata)

    with pytest.raises(ValueError, match="no longer wraps native StaVIA/VIA"):
        ov.pl.trajectory_graph(
            adata,
            method="stavia",
            model=raw_model,
            key="traj_stavia",
        )
    with pytest.raises(ValueError, match="no longer wraps native StaVIA/VIA"):
        ov.pl.trajectory_projection(
            adata,
            method="stavia",
            model=raw_model,
            key="traj_stavia",
        )

    assert not hasattr(ov.pl, "lineage_probability")
    assert not hasattr(ov.pl, "plot_graph")
    assert not hasattr(ov.pl, "plot_trajectory")
    assert not hasattr(ov.pl, "plot_lineage_probability")


def test_trajectory_supports_stavia_projection_overlay():
    adata = _make_stavia_stream_adata()
    raw_model = _FakeStaVIABackend(adata)

    fig, ax = ov.pl.trajectory(
        adata,
        method="stavia",
        model=raw_model,
        key="traj_stavia",
        cluster_key="clusters",
    )

    assert ax.collections
    arrow_patches = [
        patch for patch in ax.patches if isinstance(patch, FancyArrowPatch)
    ]
    assert arrow_patches
    assert any(text.get_text() == "TS1" for text in ax.texts)
    plt.close(fig)


def test_trajectory_tree_supports_stavia_backend_model():
    adata = _make_stavia_stream_adata()
    raw_model = _FakeStaVIABackend(adata)
    adata.obs["traj_stavia_pseudotime"] = raw_model.single_cell_pt_markov
    adata.uns["traj_stavia"]["pseudotime_key"] = "traj_stavia_pseudotime"

    fig, ax = ov.pl.trajectory_tree(
        adata,
        method="stavia",
        model=raw_model,
        key="traj_stavia",
        cluster_key="clusters",
        legend_loc=False,
    )

    assert ax.get_ylabel() == "traj_stavia_pseudotime"
    assert ax.get_legend() is None
    assert ax.yaxis_inverted()
    arrow_patches = [
        patch for patch in ax.patches if isinstance(patch, FancyArrowPatch)
    ]
    assert arrow_patches
    assert any(text.get_text() == "TS1" for text in ax.texts)
    cell_collection = [
        collection for collection in ax.collections
        if len(collection.get_offsets()) == adata.n_obs
    ][0]
    assert np.allclose(
        cell_collection.get_offsets()[:, 1],
        adata.obs["traj_stavia_pseudotime"].to_numpy(dtype=float),
    )
    plt.close(fig)


def test_trajectory_tree_supports_paga_graph():
    adata = ad.AnnData(
        X=np.ones((8, 2)),
        obs=pd.DataFrame(
            {
                "clusters": pd.Categorical(
                    ["A", "A", "B", "B", "C", "C", "D", "D"],
                    categories=["A", "B", "C", "D"],
                ),
                "dpt_pseudotime": [0.1, 0.2, 0.4, 0.5, 0.8, 0.9, 0.6, 0.7],
            },
            index=[f"c{i}" for i in range(8)],
        ),
    )
    adata.obsm["X_umap"] = np.array(
        [[0, 0], [0, 1], [2, 0], [2, 1], [4, 0], [4, 1], [2, 3], [3, 3]],
        dtype=float,
    )
    adata.uns["paga"] = {
        "groups": "clusters",
        "connectivities_tree": sparse.csr_matrix(
            np.array(
                [
                    [0, 1, 0, 0],
                    [1, 0, 1, 1],
                    [0, 1, 0, 0],
                    [0, 1, 0, 0],
                ],
                dtype=float,
            )
        ),
    }
    fig, ax = ov.pl.trajectory_tree(
        adata,
        method="paga",
        basis="X_umap",
        groups="clusters",
        pseudotime="dpt_pseudotime",
        color="clusters",
    )
    assert ax.get_ylabel() == "dpt_pseudotime"
    assert ax.yaxis_inverted()
    assert len(ax.lines) == 3
    assert all(mcolors.same_color(line.get_color(), "#1A1A1A") for line in ax.lines)
    arrow_patches = [
        patch for patch in ax.patches if isinstance(patch, FancyArrowPatch)
    ]
    assert len(arrow_patches) == 3
    cell_collection = [
        collection for collection in ax.collections
        if len(collection.get_offsets()) == adata.n_obs
    ][0]
    assert all(line.get_zorder() > cell_collection.get_zorder() for line in ax.lines)
    assert all(patch.get_zorder() > cell_collection.get_zorder() for patch in arrow_patches)
    assert np.allclose(
        cell_collection.get_offsets()[:, 1],
        adata.obs["dpt_pseudotime"].to_numpy(dtype=float),
    )
    branch_labels = [text.get_text() for text in ax.texts]
    assert branch_labels == ["B"]
    plt.close(fig)
