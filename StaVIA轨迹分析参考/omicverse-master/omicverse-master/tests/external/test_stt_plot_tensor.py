import types
import warnings

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


def test_plot_pathway_avoids_deprecated_get_cmap():
    from matplotlib import MatplotlibDeprecationWarning

    from omicverse.external.STT.pl._plot_tensor import plot_pathway

    adata = types.SimpleNamespace(
        uns={
            "pathway_select": {"p1": [], "p2": []},
            "pathway_embedding": np.array([[0.0, 0.0], [1.0, 1.0]]),
            "pathway_labels": np.array([0, 1]),
        }
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", MatplotlibDeprecationWarning)
        plot_pathway(adata)
    plt.close("all")
