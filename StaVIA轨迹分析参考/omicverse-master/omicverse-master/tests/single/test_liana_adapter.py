from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.axes import Axes
from matplotlib.figure import Figure


matplotlib.use("Agg")

try:
    import omicverse as ov
except Exception as exc:  # pragma: no cover - environment guard
    ov = None
    pytestmark = pytest.mark.skip(reason=f"omicverse import failed in test env: {exc}")


@pytest.fixture()
def liana_res() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["B", "B", "T", "T"],
            "target": ["T", "Myeloid", "B", "Myeloid"],
            "ligand_complex": ["CXCL13", "TNF", "IL7", "MIF"],
            "receptor_complex": ["CXCR5", "TNFRSF1A", "IL7R", "CD74_CXCR4"],
            "magnitude_rank": [0.02, 0.10, 0.30, 0.05],
            "specificity_rank": [0.01, 0.04, 0.15, 0.03],
            "lr_means": [4.1, 2.5, 1.2, 3.3],
            "cellphone_pvals": [0.001, 0.02, 0.20, 0.01],
        }
    )


@pytest.fixture()
def classification_reference() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "interaction_name_2": ["CXCL13 - CXCR5", "MIF - (CD74+CXCR4)"],
            "pathway_name": ["CXCL", "MIF"],
        }
    )


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


def _assert_figure_and_axes(fig, ax) -> None:
    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)


def test_format_liana_results_for_viz_builds_comm_adata_from_aggregate_scores(
    liana_res: pd.DataFrame,
    classification_reference: pd.DataFrame,
) -> None:
    comm_adata = ov.single.format_liana_results_for_viz(
        liana_res=liana_res,
        score_key="magnitude_rank",
        pvalue_key="specificity_rank",
        classification={"CXCL13-CXCR5": "Chemokine", "TNF-TNFRSF1A": "TNF"},
        classification_reference=classification_reference,
    )

    assert list(comm_adata.obs.columns) == ["sender", "receiver", "cell_type_pair"]
    assert "means" in comm_adata.layers
    assert "pvalues" in comm_adata.layers
    assert comm_adata.shape == (4, 4)
    assert comm_adata.obs.loc["B|T", "sender"] == "B"
    assert comm_adata.obs.loc["B|T", "receiver"] == "T"
    assert comm_adata.var.loc["CXCL13 -> CXCR5", "classification"] == "Chemokine"
    assert comm_adata.var.loc["CXCL13 -> CXCR5", "classification_source"] == "mapping"
    assert comm_adata.var.loc["MIF -> CD74_CXCR4", "classification"] == "MIF"
    assert comm_adata.var.loc["MIF -> CD74_CXCR4", "classification_source"] == "reference:custom_reference"
    assert comm_adata.var.loc["IL7 -> IL7R", "classification"] == "Interleukin/Cytokine"
    assert comm_adata.var.loc["IL7 -> IL7R", "classification_source"] == "family"
    assert comm_adata.var.loc["CXCL13 -> CXCR5", "interacting_pair"] == "CXCL13_CXCR5"
    assert comm_adata.var.loc["CXCL13 -> CXCR5", "pair_lr"] == "CXCL13-CXCR5"
    assert comm_adata.uns["liana_classification_reference"] == "custom_reference"
    assert float(comm_adata["B|T", "CXCL13 -> CXCR5"].layers["means"][0, 0]) > float(
        comm_adata["T|B", "IL7 -> IL7R"].layers["means"][0, 0]
    )
    assert float(comm_adata["B|T", "CXCL13 -> CXCR5"].layers["pvalues"][0, 0]) < 0.05
    assert "magnitude_rank" in comm_adata.layers
    assert "specificity_rank" in comm_adata.layers


def test_format_liana_results_for_viz_rejects_unknown_classification_fallback(
    liana_res: pd.DataFrame,
) -> None:
    with pytest.raises(ValueError, match="classification_fallback"):
        ov.single.format_liana_results_for_viz(
            liana_res=liana_res,
            score_key="magnitude_rank",
            pvalue_key="specificity_rank",
            classification_reference=None,
            classification_fallback="family1",
        )


def test_formatted_liana_comm_adata_feeds_ccc_plots(
    liana_res: pd.DataFrame,
    classification_reference: pd.DataFrame,
) -> None:
    comm_adata = ov.single.format_liana_results_for_viz(
        liana_res=liana_res,
        score_key="magnitude_rank",
        pvalue_key="specificity_rank",
        classification_reference=classification_reference,
    )

    fig1, ax1 = ov.pl.ccc_heatmap(
        comm_adata,
        plot_type="dot",
        display_by="interaction",
        top_n=3,
        show=False,
    )
    _assert_figure_and_axes(fig1, ax1)

    fig2, ax2 = ov.pl.ccc_network_plot(
        comm_adata,
        plot_type="circle",
        display_by="interaction",
        top_n=3,
        show=False,
    )
    _assert_figure_and_axes(fig2, ax2)

    fig3, ax3 = ov.pl.ccc_stat_plot(
        comm_adata,
        plot_type="bar",
        display_by="interaction",
        group_by="interaction",
        top_n=3,
        show=False,
    )
    _assert_figure_and_axes(fig3, ax3)

    fig4, ax4 = ov.pl.ccc_heatmap(
        comm_adata,
        plot_type="heatmap",
        display_by="aggregation",
        signaling="TNF",
        show=False,
    )
    _assert_figure_and_axes(fig4, ax4)

    fig5, ax5 = ov.pl.ccc_stat_plot(
        comm_adata,
        plot_type="pathway_summary",
        top_n=4,
        min_expression=0.0,
        strength_threshold=0.0,
        pvalue_threshold=0.2,
        min_significant_pairs=1,
        show=False,
    )
    _assert_figure_and_axes(fig5, ax5)
