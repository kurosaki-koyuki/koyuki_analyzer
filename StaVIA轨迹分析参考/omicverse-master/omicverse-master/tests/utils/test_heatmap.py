import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from anndata import AnnData
from scipy import sparse


def test_plot_heatmap_accepts_sparse_view():
    from omicverse.utils._heatmap import plot_heatmap

    matrix = sparse.csr_matrix([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    adata = AnnData(matrix)
    adata.var_names = ["g1", "g2"]
    adata.obs["latent_time"] = [0.0, 1.0, 2.0]
    adata.layers["Ms"] = matrix.copy()

    grid = plot_heatmap(
        adata,
        ["g1", "g2"],
        n_convolve=None,
        row_cluster=False,
        col_cluster=False,
        show=False,
    )

    assert grid is not None
    plt.close(grid.fig)


def test_make_dense_accepts_sparse_matrix_without_matrix_shortcuts():
    """SciPy sparse matrices no longer expose the ``.A`` and ``.A1`` aliases."""
    from omicverse.utils._heatmap import make_dense

    matrix = sparse.csr_matrix([[1.0, 2.0], [3.0, 4.0]])

    result = make_dense(matrix)

    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, [[1.0, 2.0], [3.0, 4.0]])


def test_make_dense_preserves_matrix_vector_semantics():
    from omicverse.utils._heatmap import make_dense

    result = make_dense(np.matrix([[1.0, 2.0]]))

    np.testing.assert_array_equal(result, [1.0, 2.0])


def test_interpret_colorkey_densifies_sparse_gene_vector():
    from omicverse.utils._heatmap import interpret_colorkey

    class SparseExpressionAdata:
        var_names = ["g1"]
        layers = {}
        raw = None
        obs = pd.DataFrame()

        @staticmethod
        def obs_vector(key, layer=None):
            assert key == "g1"
            assert layer is None
            return sparse.csr_matrix([[1.0], [2.0], [3.0]])

    result = interpret_colorkey(SparseExpressionAdata(), "g1")

    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, [1.0, 2.0, 3.0])


def test_set_colors_accepts_sequence_palette():
    from omicverse.utils._heatmap import set_colors_for_categorical_obs

    adata = AnnData(
        np.ones((2, 1)),
        obs=pd.DataFrame(
            {"group": pd.Categorical(["A", "B"])},
            index=["c1", "c2"],
        ),
    )

    set_colors_for_categorical_obs(adata, "group", ("red", "blue"))

    assert list(adata.uns["group_colors"]) == ["#ff0000", "#0000ff"]
